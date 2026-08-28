# Cat-Ear Bubble and Dialogue Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the old white Tk bubble with the selected cat-ear bow PNG skin and a bundled cute Chinese font, then provide 200 validated random phrases for each of the three six-frame actions.

**Architecture:** Dialogue content lives in an asset JSON and is loaded through a focused `DialogueChooser` that prevents immediate repeats per action. A `BubbleComposer` combines the PNG body, an orientation-specific PNG tail, and Pillow-rendered text into one RGBA image; `BubbleWindow` displays that image through the existing Win32 per-pixel-alpha renderer. Packaging embeds all data in the one-file EXE while keeping font licensing visible in the delivery folder.

**Tech Stack:** Python 3.11+, Pillow 11, Tkinter window lifecycle, Win32 `UpdateLayeredWindow`, pytest 8, PyInstaller 6, JSON, Google Fonts ZCOOL KuaiLe under SIL OFL 1.1.

## Global Constraints

- Keep the runtime actions exactly `jump`, `squash`, and `shake`, with exactly six archived `512x768 RGBA` frames per action.
- Keep click order `jump -> squash -> shake`; an ignored click while animation is busy must not show a phrase.
- Provide exactly 200 globally unique phrases per action, 600 total; every phrase has 6–10 Unicode characters, and at least 90% have 7–9 characters.
- Use the selected pink cat-ear and bow visual style, real PNG Alpha, no color key, no thick white edge, no rectangular background, and no drop shadow.
- Draw phrase text at runtime with bundled `ZCOOLKuaiLe-Regular.ttf`; do not install a system font.
- A successful action chooses uniformly from its own pool while excluding only that action's immediately previous phrase.
- Preserve drag, wheel resize, size menu, topmost toggle, multi-monitor bounds, single-instance startup, and direct EXE launch behavior.
- Do not modify the 18 archived character keyframes or restore the 30-frame runtime assets.

---

### Task 1: Build the prioritized 600-phrase library and deterministic validation

**Files:**
- Create: `assets/dialogue/phrases.json`
- Create: `src/desktop_pet/dialogue.py`
- Create: `tools/validate_dialogue.py`
- Create: `tests/test_dialogue.py`

**Interfaces:**
- Produces: `load_phrase_pools(path: Path | None = None) -> dict[str, tuple[str, ...]]`.
- Produces: `validate_phrase_pools(pools: Mapping[str, Sequence[str]]) -> None`, raising `ValueError` with the action and failing phrase.
- Produces: `DialogueChooser(pools, rng).choose(action: str) -> str`, with per-action last-phrase state.
- Leaves the existing `model.py` phrase shim untouched until Task 3 moves its only runtime caller, so the branch stays green after this task.

- [ ] **Step 1: Write failing dialogue structure and chooser tests**

```python
from random import Random

import pytest

from desktop_pet.dialogue import DialogueChooser, load_phrase_pools, validate_phrase_pools


def test_packaged_dialogue_has_three_global_unique_200_phrase_pools():
    pools = load_phrase_pools()
    assert set(pools) == {"jump", "squash", "shake"}
    assert {key: len(value) for key, value in pools.items()} == {
        "jump": 200,
        "squash": 200,
        "shake": 200,
    }
    flattened = [phrase for values in pools.values() for phrase in values]
    assert len(set(flattened)) == 600
    assert all(6 <= len(phrase) <= 10 for phrase in flattened)
    assert sum(7 <= len(phrase) <= 9 for phrase in flattened) >= 540


def test_dialogue_chooser_uses_only_requested_action_and_avoids_immediate_repeat():
    pools = {
        "jump": ("跳高高看云朵", "猫猫今天要起飞"),
        "squash": ("压成软软小团子", "回弹成功喵喵喵"),
        "shake": ("左右摇摇醒醒神", "抖抖耳朵精神啦"),
    }
    chooser = DialogueChooser(pools, Random(3))
    first = chooser.choose("jump")
    second = chooser.choose("jump")
    assert first in pools["jump"]
    assert second in pools["jump"]
    assert second != first


def test_dialogue_validation_rejects_bad_count_length_and_duplicates():
    with pytest.raises(ValueError):
        validate_phrase_pools({"jump": ("太短",), "squash": (), "shake": ()})
```

- [ ] **Step 2: Run the dialogue tests and confirm RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_dialogue.py -q`

Expected: collection fails with `ModuleNotFoundError: No module named 'desktop_pet.dialogue'`.

- [ ] **Step 3: Write the three action-specific pools**

Create UTF-8 JSON with exactly this shape:

```json
{
  "jump": ["跳高高看云朵", "猫猫今天要起飞"],
  "squash": ["压成软软小团子", "回弹成功喵喵喵"],
  "shake": ["左右摇摇醒醒神", "抖抖耳朵精神啦"]
}
```

Expand each array to exactly 200 original phrases. Use five 40-phrase semantic groups per action from the approved design. Keep every final phrase globally unique, 6–10 characters, cute first-person cat voice, and keep at least 180 phrases per action at 7–9 characters. Use compact kaomoji only where the entire string still passes the same limits.

- [ ] **Step 4: Implement loading, validation, and no-repeat random choice**

```python
class DialogueChooser:
    def __init__(self, pools, rng):
        self._pools = {action: tuple(values) for action, values in pools.items()}
        if any(not values for values in self._pools.values()):
            raise ValueError("dialogue pools must be non-empty")
        self._rng = rng
        self._last: dict[str, str] = {}

    def choose(self, action: str) -> str:
        pool = self._pools[action]
        last = self._last.get(action)
        choices = pool if last is None else tuple(p for p in pool if p != last)
        phrase = self._rng.choice(choices)
        self._last[action] = phrase
        return phrase
```

`load_phrase_pools()` must read `asset_path("assets", "dialogue", "phrases.json")` with UTF-8, call `validate_phrase_pools()`, and return immutable tuples. `validate_phrase_pools()` must enforce exact keys, exact counts, string type, trimmed non-empty values, 6–10 character length, global uniqueness, and the 90% 7–9 character rule. `DialogueChooser` accepts smaller non-empty pools in focused unit tests but production construction always receives the already validated packaged data.

- [ ] **Step 5: Add a command-line validation report**

`tools/validate_dialogue.py` must load the JSON, call `validate_phrase_pools`, print per-action counts plus total unique count, and exit nonzero on validation failure. Its successful final line must be `dialogue validation passed: 600 unique phrases`.

- [ ] **Step 6: Run tests and show the user the library**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_dialogue.py -q`

Run: `.\.venv\Scripts\python.exe tools\validate_dialogue.py`

Expected: all dialogue tests pass and validator reports 200 phrases for each action and 600 unique total. Copy `assets/dialogue/phrases.json` to `交付/台词库-600句.json` for user review without waiting for later tasks.

- [ ] **Step 7: Commit the prioritized library**

```powershell
git add assets/dialogue/phrases.json src/desktop_pet/dialogue.py tools/validate_dialogue.py tests/test_dialogue.py
git commit -m "feat: add 600 action-specific pet phrases"
```

---

### Task 2: Acquire the distributable font and produce clean bubble image assets

**Files:**
- Create: `assets/fonts/ZCOOLKuaiLe-Regular.ttf`
- Create: `assets/fonts/OFL.txt`
- Create: `THIRD_PARTY_NOTICES.txt`
- Create: `assets/bubble/cat-ear-bow-body.png`
- Create: `assets/bubble/tail-down.png`
- Create: `assets/bubble/tail-up.png`
- Create: `assets/bubble/tail-left.png`
- Create: `assets/bubble/tail-right.png`
- Create: `tests/test_bubble_assets.py`

**Interfaces:**
- Produces: one `768x208 RGBA` body and four `80x80 RGBA` directional tail overlays with fully transparent outer borders.
- Produces: an OFL font loaded directly by Pillow from `asset_path("assets", "fonts", "ZCOOLKuaiLe-Regular.ttf")`.

- [ ] **Step 1: Write failing font and PNG invariant tests**

```python
from PIL import Image, ImageFont

from desktop_pet.paths import asset_path


def test_zcool_font_loads_and_covers_approved_chinese_sample():
    font = ImageFont.truetype(asset_path("assets", "fonts", "ZCOOLKuaiLe-Regular.ttf"), 28)
    assert font.getbbox("猫猫今天要起飞") is not None


def test_bubble_assets_are_rgba_with_transparent_outer_borders():
    expected = {"cat-ear-bow-body.png": (768, 208)} | {
        f"tail-{direction}.png": (80, 80)
        for direction in ("down", "up", "left", "right")
    }
    for name, size in expected.items():
        image = Image.open(asset_path("assets", "bubble", name))
        assert image.mode == "RGBA"
        assert image.size == size
        alpha = image.getchannel("A")
        assert alpha.getextrema() == (0, 255)
        assert all(alpha.getpixel((x, 0)) == 0 for x in range(image.width))
        assert all(alpha.getpixel((x, image.height - 1)) == 0 for x in range(image.width))
```

- [ ] **Step 2: Run asset tests and confirm RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_bubble_assets.py -q`

Expected: missing font and PNG asset failures.

- [ ] **Step 3: Download the font and license from the verified official source**

Use the Google Fonts repository paths `ofl/zcoolkuaile/ZCOOLKuaiLe-Regular.ttf` and `ofl/zcoolkuaile/OFL.txt`. Record URL, upstream copyright, SIL OFL 1.1, file byte length, and SHA-256 in `THIRD_PARTY_NOTICES.txt`. Do not install the font into Windows.

- [ ] **Step 4: Generate and normalize the selected bubble skin**

Use the built-in `imagegen` workflow with the approved option-4 reference. Generate only a blank pink cat-ear bow bubble body and matching curled tail overlay, no text, no cat, no background, no shadow. Create four orientation overlays while keeping the body upright. Normalize output deterministically to the required sizes, zero RGB where Alpha is zero, and reject thick white or colored edge residue.

- [ ] **Step 5: Run asset tests and create a visual contact sheet**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_bubble_assets.py -q`

Create `qa/cat-ear-bubble-assets.png` showing the body and all four directions on dark and light checker-free backgrounds. Inspect it at actual desktop size before acceptance.

- [ ] **Step 6: Commit approved font and image assets**

```powershell
git add assets/fonts assets/bubble THIRD_PARTY_NOTICES.txt tests/test_bubble_assets.py qa/cat-ear-bubble-assets.png
git commit -m "assets: add cat-ear bubble skin and bundled cute font"
```

---

### Task 3: Integrate action-specific dialogue selection into click handling

**Files:**
- Modify: `src/desktop_pet/window.py`
- Modify: `src/desktop_pet/model.py`
- Modify: `tests/test_window.py`
- Modify: `tests/test_model.py`

**Interfaces:**
- Consumes: `DialogueChooser(load_phrase_pools(), Random())`.
- Produces: `PetWindow.dialogue`, used only after `animation.play(action)` succeeds.

- [ ] **Step 1: Write a failing click-to-action-pool test**

```python
def test_each_successful_click_chooses_from_the_started_action(tk_root, loaded_frames, monkeypatch):
    window, _renderer = make_window(tk_root, loaded_frames)
    chosen: list[str] = []
    shown: list[str] = []
    monkeypatch.setattr(window.animation, "play", lambda action: True)
    monkeypatch.setattr(window.dialogue, "choose", lambda action: chosen.append(action) or f"{action}台词喵喵")
    monkeypatch.setattr(window.bubble, "show_message", lambda text, *_: shown.append(text))
    window.trigger_next_action()
    window.trigger_next_action()
    window.trigger_next_action()
    assert chosen == ["jump", "squash", "shake"]
    assert shown == ["jump台词喵喵", "squash台词喵喵", "shake台词喵喵"]
```

- [ ] **Step 2: Run the test and confirm RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_window.py::test_each_successful_click_chooses_from_the_started_action -q`

Expected: `PetWindow` has no `dialogue` attribute.

- [ ] **Step 3: Inject the dialogue chooser and replace `choose_phrase`**

Construct `self.dialogue = DialogueChooser(load_phrase_pools(), self._rng)` in `PetWindow.__init__`. In `trigger_next_action`, retain the current busy and `animation.play` gates, then call `self.dialogue.choose(action)` exactly once and pass the result to `bubble.show_message`.

After the caller is green, remove `PHRASES` and `choose_phrase` from `model.py` and remove their old tests; `ACTIONS`, geometry helpers, and action cycling remain unchanged.

- [ ] **Step 4: Run focused and model tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_window.py tests/test_model.py tests/test_dialogue.py -q`

Expected: all selected tests pass; old tests that assert the three hard-coded phrases are removed or replaced by dialogue-module tests.

- [ ] **Step 5: Commit runtime dialogue integration**

```powershell
git add src/desktop_pet/window.py src/desktop_pet/model.py tests/test_window.py tests/test_model.py
git commit -m "feat: choose dialogue from the active action pool"
```

---

### Task 4: Replace the Tk Canvas bubble with per-pixel-alpha image composition

**Files:**
- Modify: `src/desktop_pet/bubble.py`
- Modify: `src/desktop_pet/model.py`
- Modify: `src/desktop_pet/window.py`
- Modify: `tests/test_window.py`
- Create: `tests/test_bubble.py`

**Interfaces:**
- Produces: `BubblePlacement(rect: Rect, tail_direction: Literal["down", "up", "left", "right"])`.
- Produces: `place_oriented_bubble(pet, sizes, screen, gap=12) -> BubblePlacement | None` while keeping `place_bubble()` as a rectangle-only compatibility wrapper.
- Produces: `BubbleComposer.render(text: str, tail_direction: str, scale: float = 1.0) -> Image.Image`.
- Updates: `BubbleWindow(parent, renderer_factory=LayeredWindowRenderer)` to render RGBA without a Canvas.

- [ ] **Step 1: Write failing composition, orientation, and window tests**

```python
def test_composer_returns_rgba_with_transparent_corners_and_visible_text():
    image = BubbleComposer().render("猫猫今天要起飞", "down")
    assert image.mode == "RGBA"
    assert image.getpixel((0, 0))[3] == 0
    assert image.getchannel("A").getextrema() == (0, 255)


def test_oriented_placement_points_tail_toward_pet():
    result = place_oriented_bubble(
        Rect(500, 500, 200, 300),
        {direction: (280, 116) for direction in ("down", "up", "left", "right")},
        Rect(0, 0, 1200, 900),
    )
    assert result.tail_direction == "down"
    assert result.rect.bottom <= 488


def test_bubble_window_uses_rgba_renderer_without_canvas(tk_root):
    renderer = FakeRenderer(tk_root.winfo_id())
    bubble = BubbleWindow(tk_root, renderer_factory=lambda _hwnd: renderer)
    bubble.show_message("猫猫今天要起飞", Rect(500, 500, 200, 300), Rect(0, 0, 1200, 900))
    assert not hasattr(bubble, "canvas")
    assert renderer.calls[-1][0].mode == "RGBA"
```

- [ ] **Step 2: Run new bubble tests and confirm RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_bubble.py tests/test_window.py -q`

Expected: missing `BubbleComposer`, `BubblePlacement`, and renderer injection failures.

- [ ] **Step 3: Implement oriented placement**

Try candidates in this order: above with `tail_direction="down"`, left with `"right"`, right with `"left"`, below with `"up"`. Require the complete orientation-specific RGBA size to stay inside the current monitor work area and not intersect the pet. Preserve the existing safe-side fallback for small screens.

- [ ] **Step 4: Implement PNG composition and text fitting**

Load the body, four tail overlays, and TTF through `asset_path`. Resize with LANCZOS; compose body and tail into a new transparent image using fixed overlap so there is no seam. Draw dark rose-brown centered text inside the body safe rectangle. Start at 28 source pixels and decrement until `textbbox` fits; never wrap or draw over the ears, bow, or tail.

- [ ] **Step 5: Implement the layered bubble window**

Create a borderless hidden `Toplevel`, initialize `LayeredWindowRenderer(window.winfo_id())`, and render the composed image at the chosen screen coordinates. Keep hide-timer cancellation, 1.8-second timeout, repositioning, topmost state, and destroy behavior. Remove all Tk Canvas body and text drawing.

- [ ] **Step 6: Run bubble, window, and layered-renderer tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_bubble.py tests/test_window.py tests/test_layered_window.py -q`

Expected: all selected tests pass and no test refers to Canvas fill colors or Tk transparent-color keys.

- [ ] **Step 7: Commit the per-pixel-alpha bubble**

```powershell
git add src/desktop_pet/bubble.py src/desktop_pet/model.py src/desktop_pet/window.py tests/test_bubble.py tests/test_window.py
git commit -m "feat: render image-skinned dialogue bubbles with alpha"
```

---

### Task 5: Add pixel-width validation, package assets, and deliver the EXE

**Files:**
- Modify: `tools/validate_dialogue.py`
- Modify: `tests/test_dialogue.py`
- Modify: `desktop_pet.spec`
- Modify: `build.ps1`
- Modify: `README.md`
- Create: `qa/cat-ear-bubble-runtime.png`
- Create: `交付/桌面宠物-6帧猫耳气泡版.exe`
- Create: `交付/站酷快乐体-OFL.txt`

**Interfaces:**
- Extends: dialogue validation with Pillow `ImageFont.getlength` against the production TTF and the bubble body safe width.
- Produces: one-file `桌面宠物-6帧猫耳气泡版.exe` with embedded keyframes, bubble PNGs, TTF, license, and dialogue JSON.

- [ ] **Step 1: Write failing pixel-width and build-data tests**

```python
def test_all_packaged_phrases_fit_the_production_bubble_font():
    pools = load_phrase_pools()
    font = ImageFont.truetype(asset_path("assets", "fonts", "ZCOOLKuaiLe-Regular.ttf"), 28)
    widths = [font.getlength(text) for values in pools.values() for text in values]
    assert min(widths) >= 120
    assert max(widths) <= 230
```

Extend `tests/test_build_script.py` to assert `desktop_pet.spec` includes `assets/bubble`, `assets/fonts`, and `assets/dialogue`, and that `build.ps1` invokes `tools\validate_dialogue.py` before PyInstaller.

- [ ] **Step 2: Run new validation and build tests and confirm RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_dialogue.py tests/test_build_script.py -q`

Expected: pixel-width or packaging assertions fail before the validator and PyInstaller data entries are added.

- [ ] **Step 3: Enforce production-font width and missing-glyph checks**

Update the validator to load the bundled TTF at size 28, require every phrase width in `[120, 230]`, and render every phrase to a temporary monochrome mask. Fail when a phrase exceeds the safe range or produces a missing-glyph replacement box. Print min, median, maximum width and per-action counts in the report.

- [ ] **Step 4: Package all required assets and licenses**

Add PyInstaller data entries for `assets/keyframes`, `assets/bubble`, `assets/fonts`, `assets/dialogue`, and `THIRD_PARTY_NOTICES.txt`. Rename the executable to `桌面宠物-6帧猫耳气泡版`. Make `build.ps1` run dialogue validation before the full tests and asset validation.

- [ ] **Step 5: Run the complete verification gate**

Run: `powershell -ExecutionPolicy Bypass -File .\build.ps1`

Expected: keyframe validation passes for 18 frames, dialogue validation passes for 600 unique phrases, all pytest suites pass, PyInstaller emits exactly one EXE, and the process exits with code 0.

- [ ] **Step 6: Perform runtime visual QA**

Launch the new EXE, click through at least nine successful actions, and verify each action draws phrases from the correct pool. Capture one screenshot showing the cat-ear bow bubble on the real desktop at medium size, plus edge-position checks above, left, right, and below the pet. Save the approved screenshot to `qa/cat-ear-bubble-runtime.png`.

- [ ] **Step 7: Copy verified deliverables and update documentation**

Copy the built EXE to `交付/桌面宠物-6帧猫耳气泡版.exe`, the complete JSON to `交付/台词库-600句.json`, and `assets/fonts/OFL.txt` to `交付/站酷快乐体-OFL.txt`. Update README with the new visual style, per-action random library behavior, no-repeat rule, bundled font, and build command.

- [ ] **Step 8: Commit packaging and final QA**

```powershell
git add tools/validate_dialogue.py tests/test_dialogue.py tests/test_build_script.py desktop_pet.spec build.ps1 README.md qa/cat-ear-bubble-runtime.png
git commit -m "build: package cat-ear bubble desktop pet"
```

- [ ] **Step 9: Run final branch review**

Generate a review package from commit `3f4f751` to HEAD, request a whole-branch code review, fix every Critical or Important finding, rerun `build.ps1`, and only then report the EXE and dialogue-library paths to the user.
