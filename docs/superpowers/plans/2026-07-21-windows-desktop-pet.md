# Windows Desktop Pet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a double-clickable Windows EXE that presents the supplied cat as a transparent, draggable, resizable desktop pet with three generated frame animations, Chinese speech bubbles, a context menu, and an always-on-top toggle.

**Architecture:** A small PySide6 application separates deterministic state/layout logic from Qt widgets. Generated action sheets are processed into normalized transparent frames by a repeatable Pillow pipeline, while the application loads those bundled frames through a PyInstaller-safe asset resolver. The final one-file GUI EXE contains all pet assets and does not depend on the original temporary image path.

**Tech Stack:** Python 3.11+, PySide6 6.x, Pillow 11.x, pytest 8.x, PyInstaller 6.x, Codex image generation.

## Global Constraints

- Preserve the supplied cat's face shape, orange-and-white coat, green eyes, collar, and realistic photographic appearance.
- Generate exactly three actions named `jump`, `squash`, and `shake`, with exactly 6 normalized PNG frames per action.
- Every normalized frame is RGBA, `512x768`, has a transparent background, and shares a centered body axis plus stable foot baseline.
- The pet starts at approximately 280 px high and clamps display height to the inclusive range 120-520 px.
- A click cycles `jump -> squash -> shake`; bubbles use random short Chinese text independently of that fixed action order.
- The bubble is opaque, does not overlap the pet, stays inside the current screen's available geometry, and hides after approximately 1.8 seconds.
- The app is frameless, absent from the taskbar, initially always on top, and exits without leaving a background process.
- `dist/桌面宠物.exe` must run without a separately installed Python interpreter.

---

## File Map

- `pyproject.toml`: dependency declarations and pytest configuration.
- `.gitignore`: excludes virtual environments, caches, build output, and generated previews while retaining accepted final frames.
- `assets/source/cat-original.png`: immutable copy of the supplied source image.
- `assets/generated/raw/*.png`: selected raw image-generation action sheets.
- `assets/pet/idle.png`: accepted transparent resting image.
- `assets/pet/{jump,squash,shake}/00.png` through `05.png`: normalized runtime frames.
- `assets/qa/action-contact-sheet.png` and `assets/qa/*.gif`: visual QA artifacts.
- `src/desktop_pet/paths.py`: source and PyInstaller asset path resolution.
- `src/desktop_pet/model.py`: action cycle, size clamping, bubble selection, and geometry calculations.
- `src/desktop_pet/assets.py`: strict frame loading and validation.
- `src/desktop_pet/animation.py`: timer-driven frame playback state.
- `src/desktop_pet/bubble.py`: opaque bubble widget and placement.
- `src/desktop_pet/window.py`: transparent pet window and mouse/menu behavior.
- `src/desktop_pet/main.py`: application startup, single-instance lock, and fatal-error handling.
- `tools/process_sprites.py`: chroma cleanup, sheet splitting, normalization, contact sheet, and GIF production.
- `tools/validate_assets.py`: command-line runtime asset contract check.
- `tests/`: unit and offscreen Qt tests.
- `desktop_pet.spec`: one-file windowed PyInstaller recipe.
- `build.ps1`: reproducible test-and-build entrypoint.
- `README.md`: end-user controls and developer rebuild instructions.

---

### Task 1: Project Skeleton and PyInstaller-Safe Paths

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/desktop_pet/__init__.py`
- Create: `src/desktop_pet/paths.py`
- Create: `tests/test_paths.py`
- Create: `assets/source/cat-original.png`

**Interfaces:**
- Consumes: the user image at `C:/Users/rog/AppData/Local/Temp/codex-clipboard-fd47e13f-f0aa-4dae-a8d8-ad5af80b6828.png`.
- Produces: `asset_path(*parts: str) -> pathlib.Path` and a stable in-repository source image.

- [ ] **Step 1: Copy the source image without modifying the temporary original**

Run:

```powershell
New-Item -ItemType Directory -Force -Path assets/source | Out-Null
Copy-Item -LiteralPath 'C:/Users/rog/AppData/Local/Temp/codex-clipboard-fd47e13f-f0aa-4dae-a8d8-ad5af80b6828.png' -Destination 'assets/source/cat-original.png'
Get-FileHash -Algorithm SHA256 'assets/source/cat-original.png'
```

Expected: `assets/source/cat-original.png` exists and PowerShell prints one SHA-256 hash.

- [ ] **Step 2: Write the failing path resolver tests**

```python
from pathlib import Path
import sys

from desktop_pet.paths import asset_path


def test_asset_path_uses_source_root(monkeypatch, tmp_path: Path):
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    resolved = asset_path("assets", "pet", "idle.png")
    assert resolved.parts[-3:] == ("assets", "pet", "idle.png")


def test_asset_path_uses_pyinstaller_root(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert asset_path("assets", "pet") == tmp_path / "assets" / "pet"
```

- [ ] **Step 3: Run the test and verify the missing module failure**

Run: `python -m pytest tests/test_paths.py -q`

Expected: FAIL during import with `ModuleNotFoundError: No module named 'desktop_pet'` or `desktop_pet.paths`.

- [ ] **Step 4: Add packaging configuration and the minimal resolver**

```toml
[build-system]
requires = ["setuptools>=75"]
build-backend = "setuptools.build_meta"

[project]
name = "desktop-cat-pet"
version = "1.0.0"
requires-python = ">=3.11"
dependencies = ["PySide6>=6.8,<7", "Pillow>=11,<12"]

[project.optional-dependencies]
dev = ["pytest>=8,<9", "PyInstaller>=6.13,<7"]

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

```python
# src/desktop_pet/paths.py
from pathlib import Path
import sys


def asset_path(*parts: str) -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    root = Path(bundle_root) if bundle_root else Path(__file__).resolve().parents[2]
    return root.joinpath(*parts)
```

`.gitignore` must contain:

```gitignore
.venv/
__pycache__/
.pytest_cache/
*.py[cod]
build/
dist/
*.spec.bak
assets/generated/work/
```

- [ ] **Step 5: Run the tests and commit**

Run: `python -m pytest tests/test_paths.py -q`

Expected: `2 passed`.

```powershell
git add .gitignore pyproject.toml src/desktop_pet tests/test_paths.py assets/source/cat-original.png
git commit -m "build: scaffold desktop pet project"
```

---

### Task 2: Generate, Process, and Validate the Three Action Sets

**Files:**
- Create: `tools/process_sprites.py`
- Create: `tools/validate_assets.py`
- Create: `tests/test_process_sprites.py`
- Create: `assets/generated/raw/jump.png`
- Create: `assets/generated/raw/squash.png`
- Create: `assets/generated/raw/shake.png`
- Create: `assets/pet/idle.png`
- Create: `assets/pet/{jump,squash,shake}/00.png` through `05.png`
- Create: `assets/qa/action-contact-sheet.png`
- Create: `assets/qa/{jump,squash,shake}.gif`

**Interfaces:**
- Consumes: `assets/source/cat-original.png`, three selected image-generation sheets, `process_sheet(sheet: Image.Image, action: str) -> list[Image.Image]`.
- Produces: the exact runtime frame directory contract consumed by `load_frame_paths()` in Task 4.

- [ ] **Step 1: Write failing deterministic image-pipeline tests**

```python
from PIL import Image

from tools.process_sprites import clear_border_chroma, normalize_sprite, split_grid


def test_split_grid_returns_six_equal_cells():
    sheet = Image.new("RGB", (300, 200), "blue")
    cells = split_grid(sheet, columns=3, rows=2)
    assert len(cells) == 6
    assert {cell.size for cell in cells} == {(100, 100)}


def test_clear_border_chroma_preserves_center_subject():
    image = Image.new("RGB", (12, 12), (0, 0, 255))
    for x in range(4, 8):
        for y in range(3, 10):
            image.putpixel((x, y), (230, 170, 110))
    result = clear_border_chroma(image, tolerance=55)
    assert result.getpixel((0, 0))[3] == 0
    assert result.getpixel((5, 5))[3] == 255


def test_normalize_sprite_uses_runtime_canvas_and_baseline():
    image = Image.new("RGBA", (80, 120), (0, 0, 0, 0))
    for x in range(20, 60):
        for y in range(10, 110):
            image.putpixel((x, y), (255, 120, 30, 255))
    result = normalize_sprite(image, canvas=(512, 768), margin=32)
    assert result.size == (512, 768)
    assert result.mode == "RGBA"
    assert result.getbbox()[3] == 736
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python -m pytest tests/test_process_sprites.py -q`

Expected: FAIL importing `tools.process_sprites`.

- [ ] **Step 3: Implement the deterministic processing API**

`tools/process_sprites.py` must define these complete public contracts:

```python
from collections import deque
from pathlib import Path
from PIL import Image

CANVAS = (512, 768)
FRAME_COUNT = 6
ACTIONS = ("jump", "squash", "shake")


def split_grid(sheet: Image.Image, columns: int = 3, rows: int = 2) -> list[Image.Image]:
    if sheet.width % columns or sheet.height % rows:
        raise ValueError("sheet dimensions must be divisible by the grid")
    width, height = sheet.width // columns, sheet.height // rows
    return [sheet.crop((x * width, y * height, (x + 1) * width, (y + 1) * height))
            for y in range(rows) for x in range(columns)]


def clear_border_chroma(image: Image.Image, tolerance: int = 55) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    blue_distance = lambda rgb: abs(rgb[0]) + abs(rgb[1]) + abs(255 - rgb[2])
    queue = deque((x, y) for x in range(width) for y in (0, height - 1))
    queue.extend((x, y) for y in range(height) for x in (0, width - 1))
    visited: set[tuple[int, int]] = set()
    while queue:
        x, y = queue.popleft()
        if (x, y) in visited or blue_distance(pixels[x, y][:3]) > tolerance:
            continue
        visited.add((x, y))
        pixels[x, y] = (*pixels[x, y][:3], 0)
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height:
                queue.append((nx, ny))
    return rgba


def normalize_sprite(image: Image.Image, canvas: tuple[int, int] = CANVAS, margin: int = 32) -> Image.Image:
    bbox = image.getbbox()
    if bbox is None:
        raise ValueError("sprite is empty after background removal")
    subject = image.crop(bbox)
    max_width, max_height = canvas[0] - 2 * margin, canvas[1] - 2 * margin
    scale = min(max_width / subject.width, max_height / subject.height)
    size = (max(1, round(subject.width * scale)), max(1, round(subject.height * scale)))
    subject = subject.resize(size, Image.Resampling.LANCZOS)
    output = Image.new("RGBA", canvas, (0, 0, 0, 0))
    output.alpha_composite(subject, ((canvas[0] - size[0]) // 2, canvas[1] - margin - size[1]))
    return output


def process_sheet(sheet: Image.Image, action: str) -> list[Image.Image]:
    if action not in ACTIONS:
        raise ValueError(f"unknown action: {action}")
    return [normalize_sprite(clear_border_chroma(cell)) for cell in split_grid(sheet)]
```

The script CLI must save frames as `assets/pet/<action>/<index:02d>.png`, create one contact sheet with labelled rows, and create 10-fps looping GIF previews. `tools/validate_assets.py` must exit nonzero unless every action has six `512x768` RGBA files with at least one transparent and one opaque pixel.

- [ ] **Step 4: Run the deterministic tests**

Run: `python -m pytest tests/test_process_sprites.py -q`

Expected: `3 passed`.

- [ ] **Step 5: Generate three grounded 3x2 action sheets**

Use the installed image-generation workflow with `assets/source/cat-original.png` attached as the identity reference. Generate one sheet per call on a perfectly flat saturated blue background, no shadows, text, borders, grid lines, props, or detached effects. Each sheet must contain exactly six complete, evenly sized, non-overlapping full-body poses in reading order:

```text
jump: neutral crouch, deeper crouch, launch pose, airborne tucked pose, landing pose, neutral recovery
squash: neutral, mild vertical compression, maximum compression, tall rebound overshoot, mild compression, neutral recovery
shake: neutral, lean left, lean right, lean left, lean right, neutral recovery
```

Identity prompt lock:

```text
Same exact realistic orange-and-white Devon Rex cat from the reference photograph: same large green eyes, very large ears, white blaze and chest, orange face patches, short curly coat, black collar, facial proportions and photographic lighting. Do not redesign, cartoonize, add accessories, or change coat markings.
```

Select only sheets with exactly six readable poses and save them to `assets/generated/raw/<action>.png`.

- [ ] **Step 6: Process and visually QA only the generated assets**

Run:

```powershell
python tools/process_sprites.py --input-dir assets/generated/raw --output-dir assets/pet --qa-dir assets/qa
python tools/validate_assets.py assets/pet
```

Expected: validator prints `OK: 3 actions, 18 frames, 512x768 RGBA`.

Inspect `assets/qa/action-contact-sheet.png` plus all three GIFs. Reject and regenerate the smallest failing action when there is identity drift, missing frames, overlap, cropping, white/blue halos, body-size popping, or a wrong action sequence. Copy the accepted neutral frame to `assets/pet/idle.png`.

- [ ] **Step 7: Commit accepted assets and the deterministic pipeline**

```powershell
git add tools tests/test_process_sprites.py assets/source assets/generated/raw assets/pet assets/qa
git commit -m "feat: add generated cat animation assets"
```

---

### Task 3: Deterministic Interaction and Bubble Layout Model

**Files:**
- Create: `src/desktop_pet/model.py`
- Create: `tests/test_model.py`

**Interfaces:**
- Consumes: no Qt objects.
- Produces: `clamp_height()`, `ActionCycle.next()`, `choose_phrase()`, `Rect`, and `place_bubble()` for the window layer.

- [ ] **Step 1: Write failing behavior tests**

```python
from random import Random

from desktop_pet.model import ActionCycle, Rect, clamp_height, choose_phrase, place_bubble


def test_clamp_height_enforces_contract():
    assert clamp_height(80) == 120
    assert clamp_height(280) == 280
    assert clamp_height(700) == 520


def test_action_cycle_repeats_fixed_order():
    cycle = ActionCycle()
    assert [cycle.next() for _ in range(5)] == ["jump", "squash", "shake", "jump", "squash"]


def test_phrase_is_from_action_pool():
    assert choose_phrase("jump", Random(7)) in {"看我起飞！", "今天也要跳高高！", "猫猫升空！"}


def test_bubble_prefers_above_without_overlap():
    screen = Rect(0, 0, 1920, 1040)
    pet = Rect(1500, 650, 240, 360)
    result = place_bubble(pet, (180, 72), screen, gap=12)
    assert result.bottom <= pet.top - 12
    assert screen.contains(result)


def test_bubble_moves_to_side_when_top_space_is_missing():
    screen = Rect(0, 0, 800, 600)
    pet = Rect(300, 8, 180, 300)
    result = place_bubble(pet, (190, 72), screen, gap=12)
    assert not result.intersects(pet)
    assert screen.contains(result)
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `python -m pytest tests/test_model.py -q`

Expected: FAIL importing `desktop_pet.model`.

- [ ] **Step 3: Implement the complete model contracts**

```python
from dataclasses import dataclass
from random import Random

ACTIONS = ("jump", "squash", "shake")
PHRASES = {
    "jump": ("看我起飞！", "今天也要跳高高！", "猫猫升空！"),
    "squash": ("压扁了也能弹回来！", "软乎乎的一团！", "我还能再弹一下！"),
    "shake": ("抖抖精神！", "左右都要照顾到！", "今天也要精神满满！"),
}


def clamp_height(value: int) -> int:
    return max(120, min(520, int(value)))


class ActionCycle:
    def __init__(self) -> None:
        self._index = 0

    def next(self) -> str:
        action = ACTIONS[self._index]
        self._index = (self._index + 1) % len(ACTIONS)
        return action


def choose_phrase(action: str, rng: Random) -> str:
    return rng.choice(PHRASES[action])


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def left(self) -> int: return self.x
    @property
    def right(self) -> int: return self.x + self.width
    @property
    def top(self) -> int: return self.y
    @property
    def bottom(self) -> int: return self.y + self.height
    def contains(self, other: "Rect") -> bool:
        return self.left <= other.left and self.top <= other.top and self.right >= other.right and self.bottom >= other.bottom
    def intersects(self, other: "Rect") -> bool:
        return self.left < other.right and self.right > other.left and self.top < other.bottom and self.bottom > other.top


def place_bubble(pet: Rect, size: tuple[int, int], screen: Rect, gap: int = 12) -> Rect:
    width, height = size
    candidates = (
        Rect(pet.x + (pet.width - width) // 2, pet.top - gap - height, width, height),
        Rect(pet.left - gap - width, pet.y + (pet.height - height) // 3, width, height),
        Rect(pet.right + gap, pet.y + (pet.height - height) // 3, width, height),
        Rect(pet.x + (pet.width - width) // 2, pet.bottom + gap, width, height),
    )
    for candidate in candidates:
        if screen.contains(candidate) and not candidate.intersects(pet):
            return candidate
    x = max(screen.left, min(screen.right - width, pet.left - gap - width))
    y = max(screen.top, min(screen.bottom - height, pet.top))
    return Rect(x, y, width, height)
```

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest tests/test_model.py -q`

Expected: `5 passed`.

```powershell
git add src/desktop_pet/model.py tests/test_model.py
git commit -m "feat: add desktop pet interaction model"
```

---

### Task 4: Strict Asset Loader and Animation Controller

**Files:**
- Create: `src/desktop_pet/assets.py`
- Create: `src/desktop_pet/animation.py`
- Create: `tests/test_assets.py`
- Create: `tests/test_animation.py`

**Interfaces:**
- Consumes: `asset_path()` and the `assets/pet/<action>/00..05.png` contract.
- Produces: `load_frames() -> dict[str, Sequence[QPixmap]]`; `AnimationController.play(action: str) -> bool`; signals `frame_changed(str, int)` and `finished(str)`.

- [ ] **Step 1: Write failing loader and controller tests**

```python
# tests/test_assets.py
from pathlib import Path
import pytest
from PIL import Image

from desktop_pet.assets import find_frame_paths, validate_frame_file


def test_find_frame_paths_requires_exact_six(tmp_path: Path):
    action = tmp_path / "jump"
    action.mkdir()
    for index in range(5):
        Image.new("RGBA", (512, 768), (1, 2, 3, 255)).save(action / f"{index:02d}.png")
    with pytest.raises(RuntimeError, match="jump.*6"):
        find_frame_paths(tmp_path, "jump")


def test_validate_frame_file_requires_rgba_canvas(tmp_path: Path):
    path = tmp_path / "bad.png"
    Image.new("RGB", (256, 256), "white").save(path)
    with pytest.raises(RuntimeError, match="512x768 RGBA"):
        validate_frame_file(path)
```

```python
# tests/test_animation.py
from desktop_pet.animation import AnimationController


def test_controller_rejects_overlap_and_finishes(qapp):
    controller = AnimationController({"jump": 3}, interval_ms=1)
    frames: list[tuple[str, int]] = []
    controller.frame_changed.connect(lambda action, index: frames.append((action, index)))
    assert controller.play("jump") is True
    assert controller.play("jump") is False
    while controller.busy:
        qapp.processEvents()
    assert frames == [("jump", 0), ("jump", 1), ("jump", 2)]
```

`tests/conftest.py` must create one offscreen `QApplication`, set `QT_QPA_PLATFORM=offscreen` before importing PySide6, and provide six-frame pixmap fixtures:

```python
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def loaded_frames(qapp):
    image = QImage(512, 768, QImage.Format_RGBA8888)
    image.fill(Qt.transparent)
    for y in range(96, 736):
        for x in range(128, 384):
            image.setPixelColor(x, y, Qt.white)
    frame = QPixmap.fromImage(image)
    return {action: tuple(frame.copy() for _ in range(6)) for action in ("jump", "squash", "shake")}
```

- [ ] **Step 2: Run the tests and verify failure**

Run: `python -m pytest tests/test_assets.py tests/test_animation.py -q`

Expected: FAIL importing the new modules.

- [ ] **Step 3: Implement strict loading and timer playback**

`assets.py` must reject missing, extra, incorrectly named, non-RGBA, non-`512x768`, fully transparent, or fully opaque frames before converting them to `QPixmap`:

```python
from pathlib import Path
from typing import Sequence
from PIL import Image
from PySide6.QtGui import QPixmap

from .model import ACTIONS
from .paths import asset_path


def find_frame_paths(root: Path, action: str) -> list[Path]:
    paths = sorted((root / action).glob("*.png"))
    expected = [f"{index:02d}.png" for index in range(6)]
    if [path.name for path in paths] != expected:
        raise RuntimeError(f"{action} must contain exactly 6 frames named 00.png through 05.png")
    return paths


def validate_frame_file(path: Path) -> None:
    with Image.open(path) as image:
        if image.mode != "RGBA" or image.size != (512, 768):
            raise RuntimeError(f"{path.name} must be 512x768 RGBA")
        minimum, maximum = image.getchannel("A").getextrema()
        if minimum != 0 or maximum != 255:
            raise RuntimeError(f"{path.name} must contain transparent background and opaque subject pixels")


def load_frames(root: Path | None = None) -> dict[str, Sequence[QPixmap]]:
    frame_root = root or asset_path("assets", "pet")
    loaded: dict[str, Sequence[QPixmap]] = {}
    for action in ACTIONS:
        paths = find_frame_paths(frame_root, action)
        for path in paths:
            validate_frame_file(path)
        pixmaps = tuple(QPixmap(str(path)) for path in paths)
        if any(pixmap.isNull() for pixmap in pixmaps):
            raise RuntimeError(f"failed to load {action} animation")
        loaded[action] = pixmaps
    return loaded
```

```python
# src/desktop_pet/animation.py
from PySide6.QtCore import QObject, QTimer, Signal


class AnimationController(QObject):
    frame_changed = Signal(str, int)
    finished = Signal(str)

    def __init__(self, frame_counts: dict[str, int], interval_ms: int = 90) -> None:
        super().__init__()
        self._frame_counts = frame_counts
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._advance)
        self._action: str | None = None
        self._index = 0

    @property
    def busy(self) -> bool:
        return self._action is not None

    def play(self, action: str) -> bool:
        if self.busy or action not in self._frame_counts:
            return False
        self._action, self._index = action, 0
        self.frame_changed.emit(action, 0)
        self._index = 1
        self._timer.start()
        return True

    def _advance(self) -> None:
        assert self._action is not None
        if self._index < self._frame_counts[self._action]:
            self.frame_changed.emit(self._action, self._index)
            self._index += 1
            return
        action = self._action
        self._timer.stop()
        self._action = None
        self.finished.emit(action)
```

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest tests/test_assets.py tests/test_animation.py -q`

Expected: `4 passed` or more, including the two explicit contract tests.

```powershell
git add src/desktop_pet/assets.py src/desktop_pet/animation.py tests/conftest.py tests/test_assets.py tests/test_animation.py
git commit -m "feat: load and play pet animation frames"
```

---

### Task 5: Opaque Bubble and Transparent Pet Window

**Files:**
- Create: `src/desktop_pet/bubble.py`
- Create: `src/desktop_pet/window.py`
- Create: `tests/test_window.py`

**Interfaces:**
- Consumes: `ActionCycle`, `choose_phrase`, `place_bubble`, `load_frames`, and `AnimationController`.
- Produces: `BubbleWidget.show_message(text, pet_rect, screen_rect)` and `PetWindow` with drag, click, wheel, size presets, topmost toggle, and exit action.

- [ ] **Step 1: Write failing offscreen widget tests**

```python
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QWheelEvent

from desktop_pet.window import PetWindow


def test_window_contract(qapp, loaded_frames):
    window = PetWindow(loaded_frames)
    assert window.windowFlags() & Qt.FramelessWindowHint
    assert window.windowFlags() & Qt.Tool
    assert window.windowFlags() & Qt.WindowStaysOnTopHint
    assert window.display_height == 280
    assert {action.text() for action in window.menu.actions()} >= {"小", "中", "大", "始终置顶", "退出"}


def test_size_presets_and_topmost_toggle(qapp, loaded_frames):
    window = PetWindow(loaded_frames)
    window.set_display_height(40)
    assert window.display_height == 120
    window.set_display_height(900)
    assert window.display_height == 520
    window.set_always_on_top(False)
    assert not window.windowFlags() & Qt.WindowStaysOnTopHint


def test_click_cycles_actions_but_drag_does_not(qapp, loaded_frames, monkeypatch):
    window = PetWindow(loaded_frames)
    played: list[str] = []
    monkeypatch.setattr(window.animation, "play", lambda action: played.append(action) or True)
    window.handle_left_release(QPoint(100, 100), QPoint(102, 102))
    window.handle_left_release(QPoint(100, 100), QPoint(150, 150))
    window.handle_left_release(QPoint(100, 100), QPoint(101, 101))
    assert played == ["jump", "squash"]
```

- [ ] **Step 2: Run the tests and verify failure**

Run: `python -m pytest tests/test_window.py -q`

Expected: FAIL importing `desktop_pet.window`.

- [ ] **Step 3: Implement BubbleWidget**

`BubbleWidget` must be a separate frameless `Qt.Tool` window with `WA_TranslucentBackground` and `WA_TransparentForMouseEvents`. Its custom paint event draws an opaque `(255,255,255,255)` rounded rectangle, a solid white tail, a dark 1-pixel outline, and centered dark Chinese text. `show_message()` calculates geometry with `place_bubble()`, raises the bubble, and starts a single-shot 1800-ms hide timer.

Required signature:

```python
def show_message(self, text: str, pet_rect: QRect, screen_rect: QRect) -> None:
    self.text = text
    self.adjustSize()
    logical = place_bubble(to_rect(pet_rect), (self.width(), self.height()), to_rect(screen_rect))
    self.setGeometry(logical.x, logical.y, logical.width, logical.height)
    self.show()
    self.raise_()
    self._hide_timer.start(1800)
```

- [ ] **Step 4: Implement PetWindow behavior**

Use flags `Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint`, attribute `WA_TranslucentBackground`, and a transparent central `QLabel`. Keep a press-global-position plus window-origin pair; move only after an 8-pixel Manhattan-distance threshold. A release below the threshold calls `trigger_next_action()`; larger movement is drag-only.

Required contracts:

```python
SIZE_PRESETS = {"小": 180, "中": 280, "大": 420}

def _apply_pixmap(self, pixmap: QPixmap, anchor: QPoint | None = None) -> None:
    anchor = anchor or QPoint(self.geometry().center().x(), self.geometry().bottom())
    scaled = pixmap.scaledToHeight(self.display_height, Qt.SmoothTransformation)
    self.label.setPixmap(scaled)
    self.label.setFixedSize(scaled.size())
    self.setFixedSize(scaled.size())
    self.move(anchor.x() - self.width() // 2, anchor.y() - self.height())


def set_display_height(self, value: int) -> None:
    anchor = QPoint(self.geometry().center().x(), self.geometry().bottom())
    self.display_height = clamp_height(value)
    self._apply_pixmap(self._current_pixmap, anchor)


def set_always_on_top(self, enabled: bool) -> None:
    geometry = self.geometry()
    flags = self.windowFlags()
    flags = flags | Qt.WindowStaysOnTopHint if enabled else flags & ~Qt.WindowStaysOnTopHint
    self.setWindowFlags(flags)
    self.setGeometry(geometry)
    self.show()
    if self.bubble.isVisible():
        self.bubble.raise_()


def handle_left_release(self, press: QPoint, release: QPoint) -> None:
    if (release - press).manhattanLength() < 8:
        self.trigger_next_action()


def trigger_next_action(self) -> None:
    action = self.action_cycle.next()
    if not self.animation.play(action):
        return
    phrase = choose_phrase(action, self._rng)
    screen = self.screen().availableGeometry()
    self.bubble.show_message(phrase, self.frameGeometry(), screen)


def show_frame(self, action: str, index: int) -> None:
    self._current_pixmap = self.frames[action][index]
    self._apply_pixmap(self._current_pixmap)


def show_at_default_position(self) -> None:
    area = self.screen().availableGeometry()
    self.move(area.right() - self.width() - 36, area.bottom() - self.height() - 36)
```

Call `show_at_default_position()` once immediately before the first `show()`. `set_display_height()` must preserve the window's bottom-center anchor, scale with `Qt.SmoothTransformation`, and reposition a visible bubble. `set_always_on_top()` must preserve geometry while changing flags and call `show()` afterward. The context menu actions call the three preset sizes, toggle topmost with a checkable action, and call `QApplication.quit()` for exit. `wheelEvent()` changes height by `+/-24` based on wheel delta.

- [ ] **Step 5: Run all widget and model tests**

Run: `python -m pytest tests/test_model.py tests/test_assets.py tests/test_animation.py tests/test_window.py -q`

Expected: all tests PASS with no Qt warnings treated as errors.

- [ ] **Step 6: Commit**

```powershell
git add src/desktop_pet/bubble.py src/desktop_pet/window.py tests/test_window.py
git commit -m "feat: add transparent desktop pet window"
```

---

### Task 6: Startup, One-File EXE, Documentation, and Final Verification

**Files:**
- Create: `src/desktop_pet/main.py`
- Create: `tests/test_main.py`
- Create: `desktop_pet.spec`
- Create: `build.ps1`
- Create: `README.md`

**Interfaces:**
- Consumes: `load_frames()` and `PetWindow`.
- Produces: `main() -> int`, a single-instance GUI process, and `dist/桌面宠物.exe`.

- [ ] **Step 1: Write failing startup tests**

```python
from desktop_pet.main import build_lock_name, configure_app


def test_lock_name_is_stable_and_user_scoped(monkeypatch):
    monkeypatch.setenv("USERNAME", "pet-tester")
    assert build_lock_name() == "desktop-cat-pet-pet-tester.lock"


def test_configure_app_sets_identity(qapp):
    configure_app(qapp)
    assert qapp.applicationName() == "桌面宠物"
    assert qapp.organizationName() == "Codex"
```

- [ ] **Step 2: Run the startup tests and verify failure**

Run: `python -m pytest tests/test_main.py -q`

Expected: FAIL importing `desktop_pet.main`.

- [ ] **Step 3: Implement startup and fatal error handling**

`main.py` must create `QApplication`, set application/organization names, acquire a `QLockFile` under `QStandardPaths.TempLocation`, and exit with code 0 if the lock cannot be acquired immediately. It must load frames before showing `PetWindow`. Catch `RuntimeError` from asset loading, show `QMessageBox.critical(None, "桌面宠物无法启动", str(error))`, and return code 1.

```python
def build_lock_name() -> str:
    import os
    username = os.environ.get("USERNAME", "user")
    return f"desktop-cat-pet-{username}.lock"


def configure_app(app: QApplication) -> None:
    app.setApplicationName("桌面宠物")
    app.setOrganizationName("Codex")


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Define the reproducible one-file build**

`desktop_pet.spec` must use `collect_data_files("desktop_pet")` plus `Tree("assets/pet", prefix="assets/pet")`, `console=False`, `name="桌面宠物"`, and one-file `EXE`. `build.ps1` must stop on errors, run `python tools/validate_assets.py assets/pet`, run `python -m pytest -q`, remove only the project-local `build` and `dist` directories after resolving them beneath the workspace, and execute `python -m PyInstaller --noconfirm desktop_pet.spec`.

Expected build output: `dist/桌面宠物.exe`.

- [ ] **Step 5: Document controls and rebuild commands**

`README.md` must state:

```markdown
# 桌面宠物

双击 `dist/桌面宠物.exe` 运行，无需安装 Python。

- 左键点击：依次播放跳跃、压扁回弹、左右抖动。
- 左键拖动：移动桌宠。
- 鼠标滚轮：缩放。
- 右键：选择小/中/大尺寸、切换始终置顶或退出。

开发者重新构建：在项目根目录运行 `powershell -ExecutionPolicy Bypass -File .\build.ps1`。
```

- [ ] **Step 6: Run the complete automated verification and build**

Run:

```powershell
python tools/validate_assets.py assets/pet
python -m pytest -q
powershell -ExecutionPolicy Bypass -File .\build.ps1
Get-Item 'dist/桌面宠物.exe' | Select-Object FullName,Length,LastWriteTime
```

Expected: asset validator OK, all tests pass, PyInstaller completes, and the EXE is present with nonzero length.

- [ ] **Step 7: Perform Windows runtime smoke and visual checks**

Launch `dist/桌面宠物.exe`, verify one process appears, and then manually check every acceptance item: transparent frameless window; initial topmost state; drag without click; three clicks cycle all actions; each bubble is opaque and outside the cat; wheel and menu sizes clamp correctly; topmost toggles; multi-monitor edge placement remains on screen; a second launch creates no second pet; Exit removes the process.

Inspect the live animation at 120, 280, and 520 px heights. If any problem is visual-asset-specific, repair only that action and rebuild. If behavior is wrong, add a reproducing test before changing code.

- [ ] **Step 8: Commit the verified deliverable metadata**

Do not commit `build/` or `dist/`. Commit source, tests, spec, script, and documentation:

```powershell
git add src/desktop_pet/main.py tests/test_main.py desktop_pet.spec build.ps1 README.md
git commit -m "build: package Windows desktop pet executable"
git status --short
```

Expected: clean working tree except intentionally untracked local build output.
